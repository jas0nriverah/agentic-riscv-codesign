(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x890 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv1114112 32))))
(let ((?x305 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x1159 (bvshl (bvadd independent_opaque_0 (_ bv17 32)) ?x305)))
(and (distinct ?x1159 ?x890) true)))))
(check-sat)
