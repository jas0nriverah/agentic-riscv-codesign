(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(declare-fun y () (_ BitVec 32))
(assert
 (let ((?x19 (bvadd x y)))
(let ((?x30 (bvsub ?x19 y)))
(and (distinct ?x30 x) true))))
(check-sat)
