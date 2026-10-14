(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x58 (bvmul x (_ bv2 32))))
(let ((?x56 (bvshl x (_ bv1 32))))
(and (distinct ?x56 ?x58) true))))
(check-sat)
