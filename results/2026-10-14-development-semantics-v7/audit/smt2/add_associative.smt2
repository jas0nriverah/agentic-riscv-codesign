(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun z () (_ BitVec 32))
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x22 (bvadd x (bvadd y z))))
(let ((?x19 (bvadd x y)))
(let ((?x20 (bvadd ?x19 z)))
(and (distinct ?x20 ?x22) true)))))
(check-sat)
