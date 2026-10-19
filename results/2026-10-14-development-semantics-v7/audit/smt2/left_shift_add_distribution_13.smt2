(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x165 (bvshl y (_ bv13 32))))
(let ((?x161 (bvshl x (_ bv13 32))))
(let ((?x166 (bvadd ?x161 ?x165)))
(let ((?x19 (bvadd x y)))
(let ((?x164 (bvshl ?x19 (_ bv13 32))))
(and (distinct ?x164 ?x166) true)))))))
(check-sat)
