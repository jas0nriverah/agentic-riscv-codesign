(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x234 (bvmul x (_ bv2097152 32))))
(let ((?x232 (bvshl x (_ bv21 32))))
(and (distinct ?x232 ?x234) true))))
(check-sat)
