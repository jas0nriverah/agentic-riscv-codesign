(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(declare-fun y () (_ BitVec 32))
(assert
 (let ((?x23 (bvadd y x)))
(let ((?x19 (bvadd x y)))
(and (distinct ?x19 ?x23) true))))
(check-sat)
