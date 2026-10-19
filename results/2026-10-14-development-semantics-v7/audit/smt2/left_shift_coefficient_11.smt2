(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x145 (bvmul x (_ bv2048 32))))
(let ((?x143 (bvshl x (_ bv11 32))))
(and (distinct ?x143 ?x145) true))))
(check-sat)
